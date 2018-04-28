import time
import hashlib


class Block(object):

    def __init__(self, index, proof, previous_hash, body, timestamp=None):
        self.index = index
        self.proof = proof
        self.previous_hash = previous_hash
        self.body = body
        self.timestamp = timestamp or time.time()

    @property
    def get_block_hash(self):
        block_string = "{}{}{}{}{}".format(self.index, self.proof, self.previous_hash, self.body, self.timestamp)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def __repr__(self):
        return "{} - {} - {} - {} - {}".format(self.index, self.proof, self.previous_hash, self.body, self.timestamp)


class BlockChain(object):

    def __init__(self):
        self.chain = []
        self.current_node_transactions = []
        self.nodes = set()
        self.create_genesis_block()

    @property
    def get_serialized_chain(self):
        return [vars(block) for block in self.chain]

    def create_genesis_block(self):
        self.create_new_block(proof=0, previous_hash=0)

    def create_new_block(self, proof, previous_hash):
        block = Block(
            index=len(self.chain),
            proof=proof,
            previous_hash=previous_hash,
            body=self.current_node_transactions
        )
        self.current_node_transactions = []  # Reset the transaction list

        self.chain.append(block)
        return block

    @staticmethod
    def is_valid_block(block, previous_block):
        if previous_block.index + 1 != block.index:
            return False

        elif previous_block.get_block_hash != block.previous_hash:
            return False

        elif not BlockChain.is_valid_proof(block.proof, previous_block.proof):
            return False

        elif block.timestamp <= previous_block.timestamp:
            return False

        return True

    def create_new_transaction(self, data):
        self.current_node_transactions.append({
            'user': data.get('user',{}),
            'job': data.get('job',{}),
            'application': data.get('application',{}),
            'mine_transactions':data.get('mine_transactions',{})
        })
        return True

    @staticmethod
    def is_valid_transaction():
        # Not Implemented
        pass

    @staticmethod
    def create_proof_of_work(previous_proof):
        """
        Generate "Proof Of Work"

        A very simple `Proof of Work` Algorithm -
            - Find a number such that, sum of the number and previous POW number is divisible by 7
        """
        proof = previous_proof + 1
        while not BlockChain.is_valid_proof(proof, previous_proof):
            proof += 1

        return proof

    @staticmethod
    def is_valid_proof(proof, previous_proof):
        return (proof + previous_proof) % 7 == 0

    @property
    def get_last_block(self):
        return self.chain[-1]

    def is_valid_chain(self):
        """
        Check if given blockchain is valid
        """
        previous_block = self.chain[0]
        current_index = 1

        while current_index < len(self.chain):

            block = self.chain[current_index]

            if not self.is_valid_block(block, previous_block):
                return False

            previous_block = block
            current_index += 1

        return True

    def mine_block(self, miner_address):
        # Sender "0" means that this node has mined a new block
        # For mining the Block(or finding the proof), we must be awarded with some amount(in our case this is 1)
        
        self.current_node_transactions[-1]['mine_transactions']={'sender':"0",
                                'recipient':miner_address,
                                'amount':1}

        last_block = self.get_last_block

        last_proof = last_block.proof
        proof = self.create_proof_of_work(last_proof)

        last_hash = last_block.get_block_hash
        block = self.create_new_block(proof, last_hash)

        return vars(block)  # Return a native Dict type object

    def create_node(self, addresses):
        for address in addresses:
            self.nodes.add(address)
        return True

    @staticmethod
    def get_block_object_from_block_data(block_data):
        return Block(
            block_data['index'],
            block_data['proof'],
            block_data['previous_hash'],
            block_data['body'],
            timestamp=block_data['timestamp']
        )
